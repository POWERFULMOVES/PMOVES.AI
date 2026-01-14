const { expect } = require("chai");
const { ethers } = require("hardhat");
const { deployCoreFixture, loadFixture, time } = require("./fixtures");

describe("GroupPurchase", function () {
  it("executes order when contributions meet target", async function () {
    const { alice, bob, supplier, groupPurchase, foodUSD } = await loadFixture(deployCoreFixture);

    const target = ethers.parseEther("8000");
    const deadline = (await time.latest()) + 14 * 24 * 60 * 60;
    await groupPurchase.connect(alice).createOrder(supplier.address, target, deadline);
    const orderId = await groupPurchase.orderCount();

    // Cooperative lead commits $5,000 (Tier 1 projection) toward the supplier block order.
    await foodUSD.connect(alice).approve(await groupPurchase.getAddress(), ethers.parseEther("5000"));
    await expect(groupPurchase.connect(alice).contribute(orderId, ethers.parseEther("5000")))
      .to.emit(groupPurchase, "ContributionReceived")
      .withArgs(orderId, alice.address, ethers.parseEther("5000"), ethers.parseEther("5000"));

    // Community cohort adds $3,000, matching the token pre-order scenario from the projections.
    await foodUSD.connect(bob).approve(await groupPurchase.getAddress(), ethers.parseEther("3000"));
    await expect(groupPurchase.connect(bob).contribute(orderId, ethers.parseEther("3000")))
      .to.emit(groupPurchase, "OrderExecuted")
      .withArgs(orderId, supplier.address, ethers.parseEther("8000"));

    const order = await groupPurchase.orders(orderId);
    expect(order.executed).to.equal(true);
    expect(await foodUSD.balanceOf(supplier.address)).to.equal(ethers.parseEther("8000"));
  });

  it("returns funds if target not met before deadline", async function () {
    const { alice, carol, supplier, groupPurchase, foodUSD } = await loadFixture(deployCoreFixture);

    const target = ethers.parseEther("8000");
    const deadline = (await time.latest()) + 7 * 24 * 60 * 60;
    await groupPurchase.connect(alice).createOrder(supplier.address, target, deadline);
    const orderId = await groupPurchase.orderCount();

    await foodUSD.connect(alice).approve(await groupPurchase.getAddress(), ethers.parseEther("3000"));
    await groupPurchase.connect(alice).contribute(orderId, ethers.parseEther("3000"));

    // A late contributor pledges $1,000 but the order still misses the $8,000 target.
    await foodUSD.connect(carol).approve(await groupPurchase.getAddress(), ethers.parseEther("1000"));
    await groupPurchase.connect(carol).contribute(orderId, ethers.parseEther("1000"));

    const aliceBalanceBefore = await foodUSD.balanceOf(alice.address);
    await time.increase(8 * 24 * 60 * 60);
    await expect(groupPurchase.connect(alice).claimRefund(orderId))
      .to.emit(groupPurchase, "RefundClaimed")
      .withArgs(orderId, alice.address, ethers.parseEther("3000"));

    const aliceBalanceAfter = await foodUSD.balanceOf(alice.address);
    expect(aliceBalanceAfter - aliceBalanceBefore).to.equal(ethers.parseEther("3000"));

    await expect(groupPurchase.connect(carol).claimRefund(orderId))
      .to.emit(groupPurchase, "RefundClaimed")
      .withArgs(orderId, carol.address, ethers.parseEther("1000"));
  });
});
